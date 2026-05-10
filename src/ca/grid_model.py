"""2D Cellular Automata grid model for floorplanning.

Each cell stores a multi-channel state vector:
  Ch 0  occupancy        : 0=empty 1=blockage 2=macro 3=stdcell region
  Ch 1  density          : [0,1] utilization estimate
  Ch 2  macro_affinity   : [0,1] attraction to macro placement
  Ch 3  boundary_pressure: [0,1] inverse distance to die boundary
  Ch 4  net_pressure     : [0,1] accumulated net connectivity load
  Ch 5  blockage         : binary hard blockage flag

Grid coordinates: (row, col) → (y, x) in core area.
Physical coordinates: cell (r,c) maps to µm position via cell_size.
"""
from __future__ import annotations

import dataclasses
from enum import IntEnum
from typing import List, Optional, Tuple

import numpy as np


class CellState(IntEnum):
    EMPTY    = 0
    BLOCKAGE = 1
    MACRO    = 2
    STDCELL  = 3


# Channel indices
CH_OCC  = 0
CH_DEN  = 1
CH_AFF  = 2
CH_BND  = 3
CH_NET  = 4
CH_BLK  = 5
N_CHAN  = 6


class CAGrid:
    """Multi-channel 2D CA grid mapped to the core area."""

    def __init__(
        self,
        rows: int,
        cols: int,
        core_area: Tuple[float, float, float, float],   # llx lly urx ury µm
        seed: int = 42,
    ) -> None:
        self.rows     = rows
        self.cols     = cols
        self.core_area = core_area
        self.rng      = np.random.default_rng(seed)

        cw = core_area[2] - core_area[0]
        ch = core_area[3] - core_area[1]
        self.cell_w   = cw / cols     # µm per cell (x)
        self.cell_h   = ch / rows     # µm per cell (y)

        # state[row, col, channel]
        self.state: np.ndarray = np.zeros((rows, cols, N_CHAN), dtype=np.float32)
        self._init_boundary_pressure()

    # ── coordinate conversion ─────────────────────────────────────────────────

    def phy_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        """Physical µm → (row, col), clamped to grid bounds."""
        col = int((x - self.core_area[0]) / self.cell_w)
        row = int((y - self.core_area[1]) / self.cell_h)
        return (
            max(0, min(self.rows - 1, row)),
            max(0, min(self.cols - 1, col)),
        )

    def grid_to_phy(self, row: int, col: int) -> Tuple[float, float]:
        """Cell centre → physical µm (x, y)."""
        x = self.core_area[0] + (col + 0.5) * self.cell_w
        y = self.core_area[1] + (row + 0.5) * self.cell_h
        return x, y

    # ── initialisation helpers ────────────────────────────────────────────────

    def _init_boundary_pressure(self) -> None:
        """Set boundary_pressure channel: higher near die edges."""
        r_idx = np.arange(self.rows, dtype=np.float32)
        c_idx = np.arange(self.cols, dtype=np.float32)
        dist_r = np.minimum(r_idx, self.rows - 1 - r_idx) / (self.rows / 2)
        dist_c = np.minimum(c_idx, self.cols - 1 - c_idx) / (self.cols / 2)
        # boundary_pressure = 1 at edges, 0 at centre
        rr, cc = np.meshgrid(dist_r, dist_c, indexing="ij")
        bnd = 1.0 - np.minimum(rr, cc)
        self.state[:, :, CH_BND] = bnd.astype(np.float32)

    def place_macro(self, r: int, c: int, w_cells: int, h_cells: int,
                    affinity: float = 1.0) -> None:
        """Mark a macro region in the grid."""
        r1, r2 = max(0, r), min(self.rows, r + h_cells)
        c1, c2 = max(0, c), min(self.cols, c + w_cells)
        self.state[r1:r2, c1:c2, CH_OCC] = CellState.MACRO
        self.state[r1:r2, c1:c2, CH_AFF] = affinity
        self.state[r1:r2, c1:c2, CH_DEN] = 1.0

    def add_blockage(self, r: int, c: int, w_cells: int, h_cells: int) -> None:
        r1, r2 = max(0, r), min(self.rows, r + h_cells)
        c1, c2 = max(0, c), min(self.cols, c + w_cells)
        self.state[r1:r2, c1:c2, CH_OCC] = CellState.BLOCKAGE
        self.state[r1:r2, c1:c2, CH_BLK] = 1.0
        self.state[r1:r2, c1:c2, CH_DEN] = 1.0

    def set_net_pressure(self, pressure_map: np.ndarray) -> None:
        """Set CH_NET from an external (rows, cols) pressure map."""
        assert pressure_map.shape == (self.rows, self.cols)
        self.state[:, :, CH_NET] = pressure_map.astype(np.float32).clip(0, 1)

    def seed_density(self, total_area: float, stdcell_density: float = 0.5) -> None:
        """Distribute standard-cell density across non-blocked cells."""
        free = self.state[:, :, CH_OCC] == CellState.EMPTY
        n_free = free.sum()
        if n_free == 0:
            return
        # Uniform base + small noise for CA diversity
        base = min(stdcell_density, 1.0)
        noise = self.rng.random((self.rows, self.cols)).astype(np.float32) * 0.05
        den = np.where(free, base + noise, self.state[:, :, CH_DEN])
        self.state[:, :, CH_DEN] = den.clip(0, 1)

    # ── snapshots ─────────────────────────────────────────────────────────────

    def occupancy(self) -> np.ndarray:
        return self.state[:, :, CH_OCC].copy()

    def density(self) -> np.ndarray:
        return self.state[:, :, CH_DEN].copy()

    def net_pressure(self) -> np.ndarray:
        return self.state[:, :, CH_NET].copy()

    def clone(self) -> "CAGrid":
        g = CAGrid.__new__(CAGrid)
        g.rows      = self.rows
        g.cols      = self.cols
        g.core_area = self.core_area
        g.cell_w    = self.cell_w
        g.cell_h    = self.cell_h
        g.rng       = np.random.default_rng()
        g.state     = self.state.copy()
        return g

    def state_delta(self, other: "CAGrid") -> float:
        return float(np.abs(self.state - other.state).max())
