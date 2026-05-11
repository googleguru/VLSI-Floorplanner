"""Unit tests for CA rule functions."""
import numpy as np
import pytest

from src.ca.grid_model import CAGrid, CH_DEN, CH_AFF, CH_OCC, CH_BLK, CellState, N_CHAN
from src.ca.rule_library import (
    density_equalization,
    connectivity_attraction,
    repulsion_separation,
    boundary_regularization,
    whitespace_smoothing,
    rule_235,
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
    rows, cols = 8, 8
    s = np.zeros((rows, cols, N_CHAN), dtype=np.float32)
    s[:, :, CH_DEN] = 0.9    # overly dense

    delta = whitespace_smoothing(s, {"sigma": 1.0, "target_utilization": 0.5})
    # Density should decrease toward target
    new_den = (s + delta)[:, :, CH_DEN]
    assert new_den.mean() < 0.9


def test_rule_235_kills_isolated_cells():
    """Isolated live cell (no live neighbours) must die under Rule 235."""
    s = np.zeros((6, 6, N_CHAN), dtype=np.float32)
    # Single active cell at (3,3), surrounded by zeros
    threshold = 0.30
    s[3, 3, CH_DEN] = threshold + 0.1
    params = {"threshold": threshold, "strength": 1.0, "survival_neighbors": 1}

    delta = rule_235(s, params)
    new_den = s[:, :, CH_DEN] + delta[:, :, CH_DEN]
    # Isolated cell should have density driven toward 0
    assert new_den[3, 3] < s[3, 3, CH_DEN], "Isolated cell should lose density"


def test_rule_235_births_adjacent_dead_cell():
    """Dead cell next to a live cluster should be seeded under Rule 235."""
    s = np.zeros((6, 6, N_CHAN), dtype=np.float32)
    threshold = 0.30
    # Live cluster at (2,2), (2,3), (3,2), (3,3) — the dead cell (2,4) is adjacent
    for r, c in [(2, 2), (2, 3), (3, 2), (3, 3)]:
        s[r, c, CH_DEN] = threshold + 0.2
    params = {"threshold": threshold, "strength": 1.0, "birth_neighbors": 1}

    delta = rule_235(s, params)
    new_den = s[:, :, CH_DEN] + delta[:, :, CH_DEN]
    # (2,4) borders active cells; its density should increase
    assert new_den[2, 4] > s[2, 4, CH_DEN], "Cell adjacent to cluster should gain density"


def test_rule_235_preserves_void():
    """True void (no active neighbours) must stay void (no fill)."""
    s = np.zeros((6, 6, N_CHAN), dtype=np.float32)
    threshold = 0.30
    # Active cluster in top-left only
    s[0, 0, CH_DEN] = threshold + 0.2
    s[0, 1, CH_DEN] = threshold + 0.2
    params = {"threshold": threshold, "strength": 1.0, "birth_neighbors": 1}

    delta = rule_235(s, params)
    # Bottom-right corner (5,5) has no active neighbours — must remain void
    assert (s[5, 5, CH_DEN] + delta[5, 5, CH_DEN]) == pytest.approx(0.0, abs=1e-6)


def test_rule_235_does_not_modify_blockages():
    """Rule 235 must never alter blockage cells."""
    s = np.zeros((6, 6, N_CHAN), dtype=np.float32)
    threshold = 0.30
    # Blockage at (3,3)
    s[3, 3, CH_BLK] = 1.0
    s[3, 3, CH_DEN] = 0.9
    # Surround with active cells so it would normally be a survivor
    for r, c in [(2, 3), (4, 3), (3, 2), (3, 4)]:
        s[r, c, CH_DEN] = threshold + 0.2
    params = {"threshold": threshold, "strength": 1.0}

    delta = rule_235(s, params)
    assert delta[3, 3, CH_DEN] == pytest.approx(0.0, abs=1e-6), \
        "Blockage cell must not be modified by rule_235"


def test_rule_235_connected_cluster_survives():
    """A connected cluster (each cell has live neighbours) must survive."""
    s = np.zeros((8, 8, N_CHAN), dtype=np.float32)
    threshold = 0.30
    init_den = threshold + 0.3
    # 3x3 solid block of active cells at centre
    s[3:6, 3:6, CH_DEN] = init_den
    params = {"threshold": threshold, "strength": 0.5, "survival_neighbors": 1}

    delta = rule_235(s, params)
    new_den = s[:, :, CH_DEN] + delta[:, :, CH_DEN]
    # Interior cells of the block (surrounded by active neighbours) must not decrease
    assert new_den[4, 4] >= s[4, 4, CH_DEN] - 1e-6, \
        "Interior cell of live cluster should not lose density"


def test_all_rules_return_correct_shape(grid_state):
    s = grid_state
    for fn in [
        density_equalization, connectivity_attraction,
        repulsion_separation, boundary_regularization,
        whitespace_smoothing, rule_235,
    ]:
        delta = fn(s, {})
        assert delta.shape == s.shape, f"{fn.__name__} returned wrong shape"
