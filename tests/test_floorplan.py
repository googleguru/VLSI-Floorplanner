"""Unit tests for floorplan modules."""
import pytest

from src.floorplan.macro_abstraction import MacroRegion, FloorplanState
from src.floorplan.overlap_repair import OverlapRepairer
from src.floorplan.fixed_outline import FixedOutlineChecker
from src.floorplan.whitespace_control import WhitespaceController


_CORE = (0.0, 0.0, 100.0, 100.0)


def make_macro(name, x, y, w=10, h=10):
    return MacroRegion(name=name, x=x, y=y, width=w, height=h)


def test_macro_overlap_detected():
    a = make_macro("A", 0, 0, 20, 20)
    b = make_macro("B", 10, 10, 20, 20)
    assert a.overlaps(b)


def test_macro_no_overlap():
    a = make_macro("A", 0, 0, 10, 10)
    b = make_macro("B", 15, 0, 10, 10)
    assert not a.overlaps(b)


def test_overlap_repair_removes_overlaps():
    macros = [
        make_macro("A", 30, 30),
        make_macro("B", 35, 35),   # overlaps A
        make_macro("C", 60, 60),
    ]
    repairer = OverlapRepairer(_CORE, min_gap=0.1)
    fixed = repairer.repair(macros)
    for i, a in enumerate(fixed):
        for j, b in enumerate(fixed):
            if i < j:
                assert not a.overlaps(b, gap=0.05), f"{a.name} overlaps {b.name}"


def test_outline_checker_inside():
    macros = [make_macro("A", 10, 10), make_macro("B", 80, 80)]
    checker = FixedOutlineChecker(_CORE)
    rpt = checker.check(macros)
    assert rpt.violations == 0
    assert rpt.success_rate == 1.0


def test_outline_checker_outside():
    macros = [make_macro("A", -5, 5)]   # x < 0
    checker = FixedOutlineChecker(_CORE)
    rpt = checker.check(macros)
    assert rpt.violations == 1


def test_outline_legalization_clamps():
    macros = [make_macro("A", -5, -5, 10, 10)]
    checker = FixedOutlineChecker(_CORE)
    checker.legalize(macros)
    assert macros[0].x >= 0.0
    assert macros[0].y >= 0.0


def test_whitespace_fragmentation_empty():
    ws = WhitespaceController(_CORE)
    score = ws.fragmentation_score([])
    # No macros → single large free area → low fragmentation
    assert score < 0.5


def test_whitespace_fragmentation_many_macros():
    ws = WhitespaceController(_CORE)
    macros = [make_macro(f"M{i}", 10 * i, 0, 8, 8) for i in range(9)]
    score_many = ws.fragmentation_score(macros)
    assert score_many >= 0.0
