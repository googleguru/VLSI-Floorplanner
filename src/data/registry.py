"""Central benchmark registry loaded from configs/benchmarks.yaml."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import yaml

from .benchmark_base import BenchmarkDesign, SkipReason, SizingMode
from .ipsd_adapter import IPSDAdapter
from .iscas_adapter import ISCASAdapter
from .synthetic_adapter import SyntheticAdapter

log = logging.getLogger(__name__)


class BenchmarkRegistry:
    """Loads benchmark entries from config, delegates file-presence checks to adapters."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._cfg: dict = {}
        self._designs: Dict[str, BenchmarkDesign] = {}
        self._load()

    # ── public interface ─────────────────────────────────────────────────────

    def all(self) -> List[BenchmarkDesign]:
        return list(self._designs.values())

    def ready(self) -> List[BenchmarkDesign]:
        return [d for d in self._designs.values() if not d.is_skipped]

    def skipped(self) -> List[BenchmarkDesign]:
        return [d for d in self._designs.values() if d.is_skipped]

    def get(self, name: str) -> Optional[BenchmarkDesign]:
        return self._designs.get(name)

    def families(self) -> List[str]:
        return list(self._cfg.get("benchmark_families", {}).keys())

    def summary(self) -> str:
        lines = [f"Registry loaded from {self.config_path}"]
        lines.append(f"  total={len(self._designs)}  ready={len(self.ready())}  skipped={len(self.skipped())}")
        for d in self.skipped():
            lines.append(f"  SKIP  {d.name}: {d.skip}")
        return "\n".join(lines)

    # ── internal ─────────────────────────────────────────────────────────────

    def _load(self) -> None:
        with open(self.config_path) as f:
            self._cfg = yaml.safe_load(f)

        families = self._cfg.get("benchmark_families", {})

        if "ipsd" in families:
            for design in IPSDAdapter.load(families["ipsd"], self.config_path.parent.parent):
                self._designs[design.name] = design

        if "iscas" in families:
            for design in ISCASAdapter.load(families["iscas"], self.config_path.parent.parent):
                self._designs[design.name] = design

        if "asap7" in families:
            from .asap7_manifest import ASAP7Adapter
            for design in ASAP7Adapter.load(families["asap7"], self.config_path.parent.parent):
                self._designs[design.name] = design

        synth_cfg = self._cfg.get("synthetic", {})
        if synth_cfg.get("enabled", True):
            for design in SyntheticAdapter.load(synth_cfg):
                self._designs[design.name] = design

        log.info(self.summary())
