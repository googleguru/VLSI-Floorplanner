"""Rule-based CA update rule implementations.

Each rule function has signature:
    rule(state: np.ndarray, params: dict, neighborhood: str) -> np.ndarray

Returns a delta array (rows, cols, N_CHAN) to add to the current state.
Rules operate purely on explainable heuristics — no learned parameters.

Rule documentation (also replicated in README):

1. density_equalization
   Move utilization mass from high-density to low-density cells.
   delta_den[r,c] = alpha * (mean_neighbor_den - den[r,c])   if |diff| > threshold

2. connectivity_attraction
   Attract high net-pressure regions toward macro affinity centres.
   delta_aff[r,c] += beta * net_pressure[r,c] * (1 - aff[r,c])
   Also nudges density toward macro boundaries.

3. repulsion_separation
   Push macro cells apart when they are too close.
   Macro affinity bleeds outward; neighbouring macros repel.
   delta_aff[r,c] -= gamma * overlap_pressure[r,c]

4. boundary_regularization
   Push content away from die edges using boundary_pressure channel.
   delta_den[r,c] -= lambda_b * bnd[r,c] * den[r,c]  (redistributes to centre)

5. whitespace_smoothing
   Apply Gaussian smoothing to density, targeting uniform utilization.
   delta_den = sigma * (gaussian_smooth(den) - den)
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from .grid_model import CH_OCC, CH_DEN, CH_AFF, CH_BND, CH_NET, CH_BLK, CellState
from .neighborhood import channel_mean_moore, channel_sum_moore, channel_sum_vn


def density_equalization(
    state: np.ndarray,
    params: dict,
    neighborhood: str = "moore",
) -> np.ndarray:
    """Rule 1: Equalise utilization density across the grid."""
    alpha     = float(params.get("alpha", 0.25))
    threshold = float(params.get("threshold", 0.05))

    den      = state[:, :, CH_DEN]
    blk      = state[:, :, CH_BLK]
    occ      = state[:, :, CH_OCC]

    if neighborhood == "moore":
        nbr_mean = channel_mean_moore(state, CH_DEN)
    else:
        nbr_sum  = channel_sum_vn(state, CH_DEN)
        count    = np.array([[
            sum(1 for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]
                if 0 <= r+dr < state.shape[0] and 0 <= c+dc < state.shape[1])
            for c in range(state.shape[1])] for r in range(state.shape[0])],
            dtype=np.float32)
        nbr_mean = nbr_sum / np.maximum(count, 1)

    diff  = nbr_mean - den
    delta_den = alpha * np.where(np.abs(diff) > threshold, diff, 0.0)

    # Do not move density into blockages or macro cells
    fixed = (blk > 0.5) | (occ == CellState.MACRO)
    delta_den[fixed] = 0.0

    delta = np.zeros_like(state)
    delta[:, :, CH_DEN] = delta_den.astype(np.float32)
    return delta


def connectivity_attraction(
    state: np.ndarray,
    params: dict,
    neighborhood: str = "moore",
) -> np.ndarray:
    """Rule 2: High net-pressure regions attract macro affinity."""
    beta            = float(params.get("beta", 0.30))
    max_net_press   = float(params.get("max_net_pressure", 1.0))

    net  = np.clip(state[:, :, CH_NET], 0, max_net_press)
    aff  = state[:, :, CH_AFF]
    blk  = state[:, :, CH_BLK]

    # Affinity increases where net pressure is high
    delta_aff = beta * net * (1.0 - aff)
    delta_aff[blk > 0.5] = 0.0

    delta = np.zeros_like(state)
    delta[:, :, CH_AFF] = delta_aff.astype(np.float32)
    return delta


def repulsion_separation(
    state: np.ndarray,
    params: dict,
    neighborhood: str = "moore",
) -> np.ndarray:
    """Rule 3: Repel macros that are in the same neighborhood."""
    gamma        = float(params.get("gamma", 0.40))
    min_gap_frac = float(params.get("min_gap_frac", 0.02))

    occ = state[:, :, CH_OCC]
    aff = state[:, :, CH_AFF]

    macro_mask = (occ == CellState.MACRO).astype(np.float32)

    # neighbor macro count
    if neighborhood == "moore":
        nbr_macro = channel_sum_moore(
            np.stack([macro_mask] + [np.zeros_like(macro_mask)] * 5, axis=-1),
            channel=0,
        )
    else:
        nbr_macro = channel_sum_vn(
            np.stack([macro_mask] + [np.zeros_like(macro_mask)] * 5, axis=-1),
            channel=0,
        )

    # Affinity is reduced where many macro neighbors exist → repulsion
    overlap_pressure = nbr_macro / max(state.shape[0] * 0.1, 1.0)
    delta_aff = -gamma * overlap_pressure * aff
    delta_aff[state[:, :, CH_BLK] > 0.5] = 0.0

    delta = np.zeros_like(state)
    delta[:, :, CH_AFF] = delta_aff.astype(np.float32)
    return delta


def boundary_regularization(
    state: np.ndarray,
    params: dict,
    neighborhood: str = "moore",
) -> np.ndarray:
    """Rule 4: Push density and affinity away from die boundary."""
    lambda_b = float(params.get("lambda_b", 0.35))

    bnd  = state[:, :, CH_BND]
    den  = state[:, :, CH_DEN]
    blk  = state[:, :, CH_BLK]

    # Reduce density at boundary cells; redistribute inward (net conservative)
    delta_den = -lambda_b * bnd * den
    delta_den[blk > 0.5] = 0.0

    delta = np.zeros_like(state)
    delta[:, :, CH_DEN] = delta_den.astype(np.float32)
    return delta


def whitespace_smoothing(
    state: np.ndarray,
    params: dict,
    neighborhood: str = "moore",
) -> np.ndarray:
    """Rule 5: Smooth density toward a target utilization."""
    sigma      = float(params.get("sigma", 1.5))
    target_util = float(params.get("target_utilization", 0.70))

    den  = state[:, :, CH_DEN]
    blk  = state[:, :, CH_BLK]

    smoothed    = gaussian_filter(den.astype(np.float64), sigma=sigma).astype(np.float32)
    # Blend toward target
    delta_den   = 0.5 * (smoothed - den) + 0.1 * (target_util - den)
    delta_den[blk > 0.5] = 0.0

    delta = np.zeros_like(state)
    delta[:, :, CH_DEN] = delta_den.astype(np.float32)
    return delta


# Registry mapping rule names → callables
RULE_REGISTRY = {
    "density_equalization":   density_equalization,
    "connectivity_attraction": connectivity_attraction,
    "repulsion_separation":   repulsion_separation,
    "boundary_regularization": boundary_regularization,
    "whitespace_smoothing":   whitespace_smoothing,
}
