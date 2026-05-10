"""Unit tests for CA rule functions."""
import numpy as np
import pytest

from src.ca.grid_model import CAGrid, CH_DEN, CH_AFF, CellState
from src.ca.rule_library import (
    density_equalization,
    connectivity_attraction,
    repulsion_separation,
    boundary_regularization,
    whitespace_smoothing,
)


@pytest.fixture
def grid_state():
    g = CAGrid(rows=8, cols=8, core_area=(0, 0, 80, 80), seed=0)
    g.seed_density(1000, 0.5)
    return g.state.copy()


def test_density_equalization_reduces_variance(grid_state):
    s = grid_state.copy()
    # Create a strong gradient
    s[:4, :, CH_DEN] = 0.9
    s[4:, :, CH_DEN] = 0.1

    delta = density_equalization(s, {"alpha": 0.5, "threshold": 0.0})
    new_den = (s + delta)[:, :, CH_DEN]
    var_before = float(s[:, :, CH_DEN].var())
    var_after  = float(new_den.var())
    assert var_after < var_before


def test_connectivity_attraction_increases_affinity(grid_state):
    s = grid_state.copy()
    s[:, :, CH_AFF] = 0.0      # reset affinity
    s[3, 3, 4] = 1.0           # high net pressure at centre

    delta = connectivity_attraction(s, {"beta": 1.0})
    assert delta[3, 3, CH_AFF] > 0.0   # affinity should increase at high-pressure cell


def test_repulsion_reduces_affinity_near_macros(grid_state):
    from src.ca.grid_model import CH_OCC
    s = grid_state.copy()
    s[2, 2, CH_OCC] = CellState.MACRO
    s[3, 3, CH_OCC] = CellState.MACRO
    s[:, :, CH_AFF] = 0.8     # high affinity everywhere

    delta = repulsion_separation(s, {"gamma": 1.0})
    # Cells with macro neighbors should see affinity decrease
    assert delta[2, 3, CH_AFF] < 0.0


def test_boundary_regularization_reduces_edge_density(grid_state):
    s = grid_state.copy()
    s[0, :, CH_DEN] = 0.9     # high density at top edge
    delta = boundary_regularization(s, {"lambda_b": 0.5})
    # Edge density should decrease
    assert delta[0, 4, CH_DEN] < 0.0


def test_whitespace_smoothing_pulls_toward_target():
    from src.ca.grid_model import N_CHAN
    rows, cols = 8, 8
    s = np.zeros((rows, cols, N_CHAN), dtype=np.float32)
    s[:, :, CH_DEN] = 0.9    # overly dense

    delta = whitespace_smoothing(s, {"sigma": 1.0, "target_utilization": 0.5})
    # Density should decrease toward target
    new_den = (s + delta)[:, :, CH_DEN]
    assert new_den.mean() < 0.9


def test_all_rules_return_correct_shape(grid_state):
    s = grid_state
    rows, cols, chans = s.shape
    for fn in [
        density_equalization, connectivity_attraction,
        repulsion_separation, boundary_regularization, whitespace_smoothing,
    ]:
        delta = fn(s, {})
        assert delta.shape == s.shape, f"{fn.__name__} returned wrong shape"
