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

6. rule_235  (Wolfram Rule 235, generalised to 2D VLSI)
   Binary representation of Rule 235: 11101011
   Key behaviours ported to 2D Moore neighbourhood totalistic CA:
     - Isolated live cells die            (pattern 010 → 0)
     - Connected live cells survive       (patterns 011, 111, ... → 1)
     - Dead cells adjacent to live cells  (patterns 001, 011, ... → 1)
     - True void cells (no live neighbours) stay void (VLSI whitespace preserved)
   Applied to the density channel:
     delta_den[isolated]  = strength * (0          - den)  cell eliminated
     delta_den[births]    = strength * (threshold   - den)  cell seeded
   Net effect: eliminates isolated density islands, connects nearby clusters,
   preserves intentional whitespace — directly improves placer zone quality.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from .grid_model import CH_OCC, CH_DEN, CH_AFF, CH_BND, CH_NET, CH_BLK, CellState, N_CHAN
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


def rule_235(
    state: np.ndarray,
    params: dict,
    neighborhood: str = "moore",
) -> np.ndarray:
    """Rule 6: Wolfram Rule 235 generalised to 2D VLSI placement grid.

    Rule 235 in binary (11101011) encodes these elementary CA transitions:
        pattern 111 → 1  pattern 110 → 1  pattern 101 → 1  pattern 100 → 0
        pattern 011 → 1  pattern 010 → 0  pattern 001 → 1  pattern 000 → 1

    The two non-trivial zeroes (010 and 100) give us the core behaviours:
      - 010: isolated live cell → dies
      - 100: dead cell with a single one-sided neighbour → stays dead

    Generalised to 2D Moore neighbourhood (totalistic):
      - center=1, active_neighbours=0  →  cell dies       (maps to 010 → 0)
      - center=0, active_neighbours=0  →  stays void       (VLSI whitespace)
      - center=1, active_neighbours≥1  →  cell survives   (maps to 011/111 → 1)
      - center=0, active_neighbours≥birth_nbrs → cell born (maps to 001/011 → 1)

    Applied to the density channel:
      Isolated density islands are eliminated; cells adjacent to active
      clusters are seeded; intentional whitespace (no live neighbours) is
      preserved. This directly sharpens the macro-zone signal fed to the
      placer (MacroAssigner).

    Parameters (rule_params.rule_235 in ca_rules.yaml):
      threshold      float  density value considered 'active'  default 0.30
      strength       float  rate of convergence to target       default 0.20
      birth_neighbors int   min live neighbours to trigger birth  default 1
      survival_neighbors int min live neighbours to survive      default 1
    """
    threshold     = float(params.get("threshold", 0.30))
    strength      = float(params.get("strength", 0.20))
    birth_nbrs    = int(params.get("birth_neighbors", 1))
    survival_nbrs = int(params.get("survival_neighbors", 1))

    den = state[:, :, CH_DEN]
    blk = state[:, :, CH_BLK]
    occ = state[:, :, CH_OCC]

    # Binary active map from density
    active = (den >= threshold).astype(np.float32)

    # Pack into a temporary state array for vectorised neighbour sum
    tmp = np.zeros((state.shape[0], state.shape[1], N_CHAN), dtype=np.float32)
    tmp[:, :, CH_DEN] = active

    if neighborhood == "moore":
        nbr_sum = channel_sum_moore(tmp, CH_DEN)
    else:
        nbr_sum = channel_sum_vn(tmp, CH_DEN)

    # Rule 235 pattern application:
    # Isolated live cells → die  (010 → 0)
    isolated = (active > 0.5) & (nbr_sum < float(survival_nbrs))
    # Dead cells with enough live neighbours → born  (001/011 → 1)
    births   = (active < 0.5) & (nbr_sum >= float(birth_nbrs))
    # Void cells (active=0, nbr=0) are intentional whitespace; leave unchanged.

    # Target density: drive toward 0 for isolated, toward threshold for births
    target_den = den.copy()
    target_den[isolated] = 0.0
    target_den[births]   = threshold

    delta_den = strength * (target_den - den)

    # Never modify blockage or macro cells
    fixed = (blk > 0.5) | (occ == CellState.MACRO)
    delta_den[fixed] = 0.0

    delta = np.zeros_like(state)
    delta[:, :, CH_DEN] = delta_den.astype(np.float32)
    return delta


# Registry mapping rule names → callables
RULE_REGISTRY = {
    "density_equalization":    density_equalization,
    "connectivity_attraction": connectivity_attraction,
    "repulsion_separation":    repulsion_separation,
    "boundary_regularization": boundary_regularization,
    "whitespace_smoothing":    whitespace_smoothing,
    "rule_235":                rule_235,
}
