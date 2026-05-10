"""Unit tests for the CA grid model and neighborhood operators."""
import numpy as np
import pytest

from src.ca.grid_model import CAGrid, CellState, CH_DEN, CH_AFF, CH_BND, CH_OCC
from src.ca.neighborhood import (
    channel_sum_moore, channel_sum_vn, channel_mean_moore,
)


@pytest.fixture
def small_grid():
    return CAGrid(rows=8, cols=8, core_area=(0, 0, 80, 80), seed=0)


def test_grid_init(small_grid):
    g = small_grid
    assert g.state.shape == (8, 8, 6)
    # boundary pressure at corners should be high (≥ 0.5)
    assert g.state[0, 0, CH_BND] >= 0.5
    # boundary pressure at centre should be low
    assert g.state[4, 4, CH_BND] < g.state[0, 0, CH_BND]


def test_place_macro(small_grid):
    g = small_grid
    g.place_macro(2, 2, w_cells=2, h_cells=2, affinity=0.9)
    assert g.state[2, 2, CH_OCC] == CellState.MACRO
    assert g.state[3, 3, CH_OCC] == CellState.MACRO
    assert g.state[2, 2, CH_DEN] == 1.0
    assert g.state[2, 2, CH_AFF] == pytest.approx(0.9)


def test_phy_to_grid_round_trip(small_grid):
    g = small_grid
    x, y = 40.0, 40.0   # centre
    r, c = g.phy_to_grid(x, y)
    rx, ry = g.grid_to_phy(r, c)
    assert abs(rx - x) <= g.cell_w
    assert abs(ry - y) <= g.cell_h


def test_seed_density(small_grid):
    g = small_grid
    g.seed_density(total_area=1000, stdcell_density=0.6)
    free = g.state[:, :, CH_OCC] == CellState.EMPTY
    mean_den = g.state[free, CH_DEN].mean()
    assert 0.4 < mean_den < 0.8


def test_state_delta(small_grid):
    g1 = small_grid
    g2 = g1.clone()
    assert g1.state_delta(g2) == pytest.approx(0.0, abs=1e-6)
    g2.state[0, 0, CH_DEN] = 0.99
    assert g1.state_delta(g2) > 0.0


def test_channel_sum_moore():
    # 3x3 grid of ones, channel 0
    state = np.ones((3, 3, 6), dtype=np.float32)
    s = channel_sum_moore(state, channel=0)
    # corner cell (0,0) has 3 Moore neighbors
    assert s[0, 0] == pytest.approx(3.0)
    # centre cell (1,1) has 8 Moore neighbors
    assert s[1, 1] == pytest.approx(8.0)


def test_channel_sum_vn():
    state = np.ones((3, 3, 6), dtype=np.float32)
    s = channel_sum_vn(state, channel=0)
    assert s[0, 0] == pytest.approx(2.0)   # only 2 VN neighbors at corner
    assert s[1, 1] == pytest.approx(4.0)   # 4 VN neighbors at centre
