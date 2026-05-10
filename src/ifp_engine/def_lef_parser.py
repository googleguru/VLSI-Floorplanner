"""Lightweight DEF/LEF parser for extracting floorplan metrics.

Parses only the fields needed for evaluation:
  - DIEAREA
  - UNITS DISTANCE MICRONS
  - COMPONENTS count
  - NETS count
  - SITE name / width / height from LEF
  - BLOCKAGES count
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Optional, Tuple


@dataclasses.dataclass
class DEFInfo:
    design:       str = ""
    db_units:     int = 1000
    die_area:     Tuple[float, float, float, float] = (0, 0, 0, 0)   # µm
    num_components: int = 0
    num_nets:     int = 0
    num_blockages: int = 0

    @property
    def die_width(self) -> float:
        return self.die_area[2] - self.die_area[0]

    @property
    def die_height(self) -> float:
        return self.die_area[3] - self.die_area[1]

    @property
    def die_area_um2(self) -> float:
        return self.die_width * self.die_height


@dataclasses.dataclass
class SiteInfo:
    name:   str = "unit"
    width:  float = 0.19    # µm
    height: float = 1.4


def parse_def(path: Path) -> DEFInfo:
    info = DEFInfo()
    if not path.exists():
        return info

    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("DESIGN "):
                info.design = s.split()[1].rstrip(";")
            elif s.startswith("UNITS DISTANCE MICRONS"):
                try:
                    info.db_units = int(s.split()[3].rstrip(";"))
                except (IndexError, ValueError):
                    pass
            elif s.startswith("DIEAREA"):
                # DIEAREA ( llx lly ) ( urx ury ) ;
                nums = re.findall(r"[-\d]+", s)
                if len(nums) >= 4:
                    scale = info.db_units
                    info.die_area = (
                        int(nums[0]) / scale,
                        int(nums[1]) / scale,
                        int(nums[2]) / scale,
                        int(nums[3]) / scale,
                    )
            elif s.startswith("COMPONENTS ") and not s.startswith("COMPONENTS ;"):
                try:
                    info.num_components = int(s.split()[1].rstrip(";"))
                except (IndexError, ValueError):
                    pass
            elif s.startswith("NETS ") and not s.startswith("NETS ;"):
                try:
                    info.num_nets = int(s.split()[1].rstrip(";"))
                except (IndexError, ValueError):
                    pass
            elif s.startswith("BLOCKAGES ") and not s.startswith("BLOCKAGES ;"):
                try:
                    info.num_blockages = int(s.split()[1].rstrip(";"))
                except (IndexError, ValueError):
                    pass
    return info


def parse_lef_site(path: Path, site_name: str = "unit") -> SiteInfo:
    info = SiteInfo(name=site_name)
    if not path.exists():
        return info

    in_site = False
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith(f"SITE {site_name}"):
                in_site = True
            elif in_site and s.startswith("END "):
                break
            elif in_site and s.startswith("SIZE"):
                # SIZE w BY h ;
                m = re.match(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", s)
                if m:
                    info.width  = float(m.group(1))
                    info.height = float(m.group(2))
    return info
