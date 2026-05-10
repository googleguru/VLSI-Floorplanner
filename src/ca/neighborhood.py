"""Neighborhood operators for Moore and von Neumann neighborhoods.

All functions return shifted views using numpy.roll (periodic) or
zero-padded slices (non-periodic). VLSI floorplanning uses non-periodic
boundaries (die edges are hard constraints).
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np


def moore_neighbors(grid: np.ndarray, r: int, c: int,
                    rows: int, cols: int) -> List[Tuple[int, int]]:
    """Return (row, col) pairs of Moore neighbors (8-connected), in-bounds only."""
    nbrs = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                nbrs.append((nr, nc))
    return nbrs


def von_neumann_neighbors(grid: np.ndarray, r: int, c: int,
                           rows: int, cols: int) -> List[Tuple[int, int]]:
    """Return (row, col) pairs of von Neumann neighbors (4-connected), in-bounds."""
    nbrs = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            nbrs.append((nr, nc))
    return nbrs


def channel_sum_moore(state: np.ndarray, channel: int) -> np.ndarray:
    """Vectorised sum of a channel over Moore neighborhood (non-periodic, zero-padded)."""
    s = state[:, :, channel]
    rows, cols = s.shape
    # Pad with zeros (width=1) and sum all 8 shifted slices
    padded = np.pad(s, 1, mode="constant", constant_values=0.0)
    out = np.zeros_like(s)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r0, r1 = 1 + dr, 1 + dr + rows
            c0, c1 = 1 + dc, 1 + dc + cols
            out += padded[r0:r1, c0:c1]
    return out


def channel_sum_vn(state: np.ndarray, channel: int) -> np.ndarray:
    """Vectorised sum of a channel over von Neumann neighborhood (non-periodic, zero-padded)."""
    s = state[:, :, channel]
    rows, cols = s.shape
    padded = np.pad(s, 1, mode="constant", constant_values=0.0)
    out = np.zeros_like(s)
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r0, r1 = 1 + dr, 1 + dr + rows
        c0, c1 = 1 + dc, 1 + dc + cols
        out += padded[r0:r1, c0:c1]
    return out


def channel_mean_moore(state: np.ndarray, channel: int) -> np.ndarray:
    """Mean over Moore neighborhood (normalised by actual neighbor count)."""
    s = state[:, :, channel]
    count = _neighbor_count_moore(s.shape)
    return channel_sum_moore(state, channel) / count


def _neighbor_count_moore(shape: tuple) -> np.ndarray:
    """Actual number of Moore neighbors per cell (accounting for boundaries)."""
    rows, cols = shape
    r_idx = np.arange(rows)
    c_idx = np.arange(cols)
    rr, cc = np.meshgrid(r_idx, c_idx, indexing="ij")
    r_cnt = np.where(rr == 0, 0, 1) + np.where(rr == rows - 1, 0, 1) + 1
    c_cnt = np.where(cc == 0, 0, 1) + np.where(cc == cols - 1, 0, 1) + 1
    return (r_cnt * c_cnt - 1).astype(np.float32).clip(1)
