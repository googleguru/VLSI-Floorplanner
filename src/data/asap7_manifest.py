"""ASAP7 PDK manifest adapter.

Validates PDK file presence before attempting any ASAP7-based design run.
Reads configs/asap7.yaml for PDK path and required file list.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import yaml

from .benchmark_base import BenchmarkDesign, SkipReason, SizingMode

log = logging.getLogger(__name__)


class ASAP7Adapter:
    @staticmethod
    def load(cfg: dict, repo_root: Path) -> List[BenchmarkDesign]:
        # Load ASAP7 PDK config
        asap7_cfg_path = repo_root / "configs" / "asap7.yaml"
        try:
            with open(asap7_cfg_path) as f:
                pdk_cfg = yaml.safe_load(f).get("asap7", {})
        except OSError:
            log.warning("asap7.yaml not found; all ASAP7 designs will be skipped.")
            pdk_cfg = {}

        pdk_dir = repo_root / pdk_cfg.get("pdk_dir", "data/pdk/asap7")
        required = pdk_cfg.get("required_files", [])
        site = pdk_cfg.get("site_name", "asap7sc7p5t_28_R_site")

        # Check all required PDK files
        pdk_skip: SkipReason | None = None
        for fname in required:
            fpath = pdk_dir / fname
            if not fpath.exists():
                pdk_skip = SkipReason("MISSING_PDK",
                    f"ASAP7 PDK file missing: {fpath}. "
                    + pdk_cfg.get("acquisition_note",
                        "Clone the ASAP7 PDK to data/pdk/asap7"))
                break

        base_dir = repo_root / cfg["base_dir"]
        sizing_mode = SizingMode(cfg.get("sizing_mode", "utilization"))
        designs: List[BenchmarkDesign] = []

        for entry in cfg.get("designs", []):
            name = entry["name"]

            skip = pdk_skip
            if not skip and entry.get("skip_reason"):
                skip = SkipReason("MANUAL", entry["skip_reason"])

            verilog = base_dir / name / entry.get("verilog", f"{name}.v")
            if not skip and not verilog.exists():
                skip = SkipReason("MISSING_VERILOG",
                    f"Verilog not found: {verilog}. "
                    "Provide a synthesized Verilog netlist for this ASAP7 design.")

            lef_path = pdk_dir / pdk_cfg.get("cell_lef", "asap7sc7p5t_28_R.lef")
            tech_lef = pdk_dir / pdk_cfg.get("tech_lef", "asap7_tech.lef")

            kwargs: dict = {}
            if sizing_mode == SizingMode.UTILIZATION:
                kwargs.update(
                    utilization  = cfg.get("default_utilization", 0.65),
                    aspect_ratio = cfg.get("default_aspect_ratio", 1.0),
                    core_space   = tuple(cfg.get("default_core_space", [4, 4, 4, 4])),
                )
            else:
                kwargs.update(
                    die_area  = tuple(cfg.get("default_die_area",  [0, 0, 300, 300])),
                    core_area = tuple(cfg.get("default_core_area", [5, 5, 295, 295])),
                )

            d = BenchmarkDesign(
                name        = name,
                family      = "asap7",
                sizing_mode = sizing_mode,
                site        = site,
                lef_path    = lef_path if lef_path.exists() else None,
                skip        = skip,
                **kwargs,
            )

            if not skip:
                d.validate_sizing()

            designs.append(d)
            status = "READY" if not skip else f"SKIP({skip.code})"
            log.info("ASAP7 %-30s %s", name, status)

        return designs
