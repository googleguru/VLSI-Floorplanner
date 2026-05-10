"""Unit tests for the IFP Tcl generator."""
import pytest
from pathlib import Path

from src.data.benchmark_base import BenchmarkDesign, SizingMode
from src.ifp_engine.tcl_generator import IFPTclGenerator


@pytest.fixture
def die_core_design(tmp_path):
    return BenchmarkDesign(
        name        = "test_dc",
        family      = "synthetic",
        sizing_mode = SizingMode.DIE_CORE,
        die_area    = (0, 0, 500, 500),
        core_area   = (10, 10, 490, 490),
        site        = "unit",
    )


@pytest.fixture
def util_design(tmp_path):
    return BenchmarkDesign(
        name         = "test_util",
        family       = "synthetic",
        sizing_mode  = SizingMode.UTILIZATION,
        utilization  = 0.70,
        aspect_ratio = 1.0,
        core_space   = (2, 2, 2, 2),
        site         = "unit",
    )


def test_die_core_tcl_has_die_area(die_core_design, tmp_path):
    gen = IFPTclGenerator(die_core_design, output_def=tmp_path / "out.def")
    tcl = gen.generate()
    assert "-die_area" in tcl
    assert "-core_area" in tcl
    assert "-utilization" not in tcl
    assert "-aspect_ratio" not in tcl


def test_util_tcl_has_utilization(util_design, tmp_path):
    gen = IFPTclGenerator(util_design, output_def=tmp_path / "out.def")
    tcl = gen.generate()
    assert "-utilization" in tcl
    assert "-aspect_ratio" in tcl
    assert "-die_area" not in tcl
    assert "-core_area" not in tcl


def test_tcl_has_site(die_core_design, tmp_path):
    gen = IFPTclGenerator(die_core_design, output_def=tmp_path / "out.def")
    tcl = gen.generate()
    assert "-site" in tcl
    assert "unit" in tcl


def test_tcl_ends_with_exit(die_core_design, tmp_path):
    gen = IFPTclGenerator(die_core_design, output_def=tmp_path / "out.def")
    tcl = gen.generate()
    assert tcl.strip().endswith("exit")


def test_make_tracks_emitted(die_core_design, tmp_path):
    tracks = [{"layer": "M1", "x_offset": 0, "x_pitch": 0.027,
                "y_offset": 0, "y_pitch": 0.027}]
    gen = IFPTclGenerator(
        die_core_design, output_def=tmp_path / "out.def",
        make_tracks=True, track_layers=tracks,
    )
    tcl = gen.generate()
    assert "make_tracks" in tcl
    assert "M1" in tcl


def test_mixed_mode_validation_raises():
    """Mixing die_core + utilization fields must raise at validation."""
    d = BenchmarkDesign(
        name="bad", family="synthetic",
        sizing_mode=SizingMode.DIE_CORE,
        die_area=(0, 0, 500, 500), core_area=(10, 10, 490, 490),
        utilization=0.70,   # illegal in die_core mode
        site="unit",
    )
    with pytest.raises(AssertionError):
        d.validate_sizing()
