"""Base data classes shared by all benchmark adapters."""
from __future__ import annotations

import dataclasses
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


class SizingMode(str, Enum):
    """OpenROAD ifp supports exactly two mutually exclusive sizing modes."""
    DIE_CORE   = "die_core"       # explicit die/core area rectangles
    UTILIZATION = "utilization"   # utilization + aspect_ratio + core_space


@dataclasses.dataclass
class SkipReason:
    code: str
    message: str

    def __str__(self) -> str:
        return f"[SKIPPED:{self.code}] {self.message}"


@dataclasses.dataclass
class MacroDef:
    name: str
    width: float    # microns
    height: float
    x: float = 0.0
    y: float = 0.0
    fixed: bool = False


@dataclasses.dataclass
class NetDef:
    name: str
    pins: List[str]  # cell_name/pin_name strings


@dataclasses.dataclass
class BenchmarkDesign:
    """Unified representation of a design ready for floorplanning."""
    name:       str
    family:     str           # "ipsd" | "iscas" | "asap7" | "synthetic"
    sizing_mode: SizingMode

    # die_core mode fields
    die_area:  Optional[Tuple[float, float, float, float]] = None   # llx lly urx ury µm
    core_area: Optional[Tuple[float, float, float, float]] = None

    # utilization mode fields
    utilization:    Optional[float] = None
    aspect_ratio:   Optional[float] = None
    core_space:     Optional[Tuple[float, float, float, float]] = None  # L B R T

    # common
    site:           str = "unit"
    macros:         List[MacroDef] = dataclasses.field(default_factory=list)
    nets:           List[NetDef]   = dataclasses.field(default_factory=list)
    num_stdcells:   int = 0

    # file paths (may be None if not yet generated)
    lef_path:  Optional[Path] = None
    def_path:  Optional[Path] = None
    lib_path:  Optional[Path] = None

    skip:      Optional[SkipReason] = None

    @property
    def is_skipped(self) -> bool:
        return self.skip is not None

    def validate_sizing(self) -> None:
        """Raise if the two sizing modes are mixed."""
        if self.sizing_mode == SizingMode.DIE_CORE:
            assert self.die_area is not None and self.core_area is not None, \
                f"{self.name}: die_core mode requires die_area and core_area"
            assert self.utilization is None and self.aspect_ratio is None, \
                f"{self.name}: die_core mode must not specify utilization/aspect_ratio"
        else:
            assert self.utilization is not None and self.aspect_ratio is not None, \
                f"{self.name}: utilization mode requires utilization and aspect_ratio"
            assert self.die_area is None and self.core_area is None, \
                f"{self.name}: utilization mode must not specify die_area/core_area"

    @property
    def core_width(self) -> float:
        if self.sizing_mode == SizingMode.DIE_CORE and self.core_area:
            return self.core_area[2] - self.core_area[0]
        return 0.0

    @property
    def core_height(self) -> float:
        if self.sizing_mode == SizingMode.DIE_CORE and self.core_area:
            return self.core_area[3] - self.core_area[1]
        return 0.0
