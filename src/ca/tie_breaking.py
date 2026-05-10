"""Deterministic tie-breaking for CA rule deltas.

When multiple rules produce exactly equal deltas for a cell, we apply a
fixed spatial bias (top-left preference) to break ties without randomness,
ensuring fully reproducible runs given the same seed.
"""
from __future__ import annotations

import numpy as np


def deterministic_tiebreak(delta: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Add a tiny spatially deterministic bias to break exact ties.

    The bias magnitude (eps) is far smaller than any meaningful rule delta,
    so it does not affect functional outcome — only tie ordering.
    """
    rows, cols, chans = delta.shape
    # Spatial gradient: smallest at (0,0), largest at (rows-1, cols-1)
    r_idx = np.arange(rows,  dtype=np.float32).reshape(-1, 1, 1)
    c_idx = np.arange(cols,  dtype=np.float32).reshape(1, -1, 1)
    bias  = eps * (r_idx / max(rows - 1, 1) + c_idx / max(cols - 1, 1))
    return delta + bias
