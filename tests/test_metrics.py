"""Unit tests for metric computation."""
import pytest

from src.floorplan.macro_abstraction import MacroRegion, FloorplanState
from src.objectives.metrics import compute_metrics
from src.data.benchmark_base import NetDef


_CORE = (0.0, 0.0, 100.0, 100.0)


def make_fp(macros):
    return FloorplanState(design="test", macros=macros, core_area=_CORE)


def test_no_overlap():
    fp = make_fp([
        MacroRegion("A", 10, 10, 20, 20),
        MacroRegion("B", 60, 60, 20, 20),
    ])
    m = compute_metrics(fp, "test")
    assert m.overlap_count == 0
    assert m.overlap_area_um2 == pytest.approx(0.0)


def test_overlap_detected():
    fp = make_fp([
        MacroRegion("A", 10, 10, 30, 30),
        MacroRegion("B", 30, 30, 30, 30),   # overlaps A
    ])
    m = compute_metrics(fp, "test")
    assert m.overlap_count == 1
    assert m.overlap_area_um2 > 0.0


def test_hpwl_computed():
    nets = [NetDef("n1", ["A/Q", "B/D"])]
    fp = make_fp([
        MacroRegion("A", 0, 0, 10, 10),
        MacroRegion("B", 90, 90, 10, 10),
    ])
    m = compute_metrics(fp, "test", nets=nets)
    # HPWL = (90-0 half perimeter x) + (90-0 y) roughly
    assert m.hpwl_um > 0.0


def test_density_variance_non_negative():
    fp = make_fp([MacroRegion("A", 10, 10, 20, 20)])
    m = compute_metrics(fp, "test")
    assert m.density_variance >= 0.0


def test_outline_success_perfect():
    fp = make_fp([
        MacroRegion("A", 5, 5, 10, 10),
        MacroRegion("B", 80, 80, 10, 10),
    ])
    m = compute_metrics(fp, "test")
    assert m.outline_success == pytest.approx(1.0)
